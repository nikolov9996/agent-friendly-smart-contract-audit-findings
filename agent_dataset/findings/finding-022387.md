---
id: 22387
severity: "High"
---

# Wrong parameter when retrieving causes a DoS in CouncilMember contract

## Description

A wrong parameter in the _retrieve() prevents the protocol from properly interacting with Sablier, causing a Denial of Service in all functions calling _retrieve().  
The CouncilMember contract is designed to interact with a Sablier stream. As time passes, the Sablier stream will unlock more TELCOIN tokens which will be available to be retrieved from CouncilMember.  
The _retrieve() internal function will be used in order to fetch the rewards from the stream and distribute them among the Council Member NFT holders (snippet reduced for simplicity):  
// CouncilMember.sol  
```solidity
function _retrieve() internal {
...
// Execute the withdrawal from the _target, which might be a Sablier stream or another protocol
_stream.execute(
_target,
abi.encodeWithSelector(
ISablierV2ProxyTarget.withdrawMax.selector,
_target,
_id,
address(this)
)
);
...
}
```
The most important part in _retrieve() regarding the vulnerability that we’ll dive into is the _stream.execute() interaction and the params it receives. In order to understand such interaction, we first need understand the importance of the _stream and the _target variables.  
Sablier allows developers to integrate Sablier via Periphery contracts, which prevents devs from dealing with the complexity of directly integrating Sablier’s Core contracts. Telcoin developers have decided to use these periphery contracts.  
Concretely, the following contracts have been used:  
• ProxyTarget (link points to an older commit because **the proxy target contracts have now been deprecated from Sablier**): stored in the _target variable, this contract acts as the target for a PRBProxy contract. It contains all the complex interactions with the underlying stream. Concretely, Telcoin uses the [withdrawMax()](https://github.com/sablier-labs/v2-periphery/blob/ba3926d2c3e059a230211077087b73afe46acf64/src/abstracts/SablierV2Proxy) function in the proxy target to withdraw all the available funds from the stream (as seen in the previous code snippet).  
• PRBProxy: stored in the _stream variable, this contract acts as a forwarding (non-upgradable) proxy, acting as a smart wallet that enables multiple contract calls within a single transaction.  
will be deployed as well. The difference is that the Telcoin protocol will not interact with that contract directly. Instead, the PRBProxy and proxy target contracts will be leveraged to perform such interactions.  
Knowing this, we can now move on to explaining Telcoin’s approach to withdrawing the available tokens from the stream. As seen in the code snippet above, the _retrieve() function will perform two steps to actually perform a withdraw from the stream:  
It will first call the _stream's execute() function (remember _stream is a PRBProxy). This function receives a target and some data as parameter, and performs a delegatecall aiming at the target:  
// https://github.com/PaulRBerg/prb-proxy/blob/main/src/PRBProxy.sol  
```solidity
/// @inheritdoc IPRBProxy
function execute(address target, bytes calldata data) external payable
...
}
INTERNAL NON-CONSTANT FUNCTIONS
/// @notice Executes a DELEGATECALL to the provided target with the provided data.
/// @dev Shared logic between the constructor and the `execute` function.
function _execute(address target, bytes memory data) internal returns (bytes
// Check that the target is a contract.
if (target.code.length == 0) {
revert PRBProxy_TargetNotContract(target);
}
// Delegate call to the target contract.
bool success;
...
}
```
In the _retrieve() function, the target where the call will be forwarded to is the _target parameter, which is a ProxyTarget contract. Concretely, the delegatecall function that will be triggered in the ProxyTarget will be withdrawMax():  
// https://github.com/sablier-labs/v2-periphery/blob/ba3926d2c3e059a230211077087cb73afe46acf64/src/abstracts/SablierV2ProxyTarget.sol#L141C5-L143C6  
```solidity
function withdrawMax(ISablierV2Lockup lockup, uint256 streamId, address to) external onlyDelegateCall {
lockup.withdrawMax(streamId, to);
}
```
As we can see, the withdrawMax() function has as parameters the lockup stream contract to withdraw from, the streamId and the address to which will receive the available funds from the stream. The vulnerability lies in the parameters passed when calling the withdrawMax() function in _retrieve(). As we can see, the first encoded parameter in the encodeWithSelector() call after the selector is the _target:  
// CouncilMember.sol  
```solidity
function _retrieve() internal {
...
// Execute the withdrawal from the _target, which might be a Sablier stream or another protocol
_stream.execute(
_target,
abi.encodeWithSelector(
ISablierV2ProxyTarget.withdrawMax.selector,
_target, // <------- This is incorrect
_id,
address(this)
)
);
...
}
```
This means that the proxy target’s withdrawMax() function will be triggered with the _target contract as the lockup parameter, which is incorrect. This will make all calls eventually execute withdrawMax() on the PRBProxy contract, always reverting.  
The parameter needed to perform the withdrawMax() call correctly is the actual Sablier lockup contract, which is currently not stored in the CouncilMember contract.  
The following diagram also summarizes the current wrong interactions for clarity:  
High. ALL withdrawals from the Sablier stream will revert, effectively causing a DoS in the _retrieve() function. Because the _retrieve() function is called in all the main protocol functions, this vulnerability essentially prevents the protocol from ever functioning correctly.

## Proof of Concept

Because the current Telcoin repo does not include actual tests with the real Sablier contracts (instead, a TestStream contract is used, which has led to not unveiling this vulnerability), [I’ve created a repository](https://github.com/0xadrii/telcoin-proof-of-concept) where the poc can be executed (the repository will be public after how any interaction (in this case, a call to the mint() function) will fail because the proper Sablier contracts are used (PRBProxy and proxy target):  
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;
import {Test, console2} from "forge-std/Test.sol";
import {SablierV2Comptroller} from "@sablier/v2-core/src/SablierV2Comptroller.sol";
import {SablierV2NFTDescriptor} from "@sablier/v2-core/src/SablierV2NFTDescriptor.sol";
import {SablierV2LockupLinear} from "@sablier/v2-core/src/SablierV2LockupLinear.sol";
import {ISablierV2Comptroller} from "@sablier/v2-core/src/interfaces/ISablierV2Comptroller.sol";
import {ISablierV2NFTDescriptor} from "@sablier/v2-core/src/interfaces/ISablierV2NFTDescriptor.sol";
import {ISablierV2LockupLinear} from "@sablier/v2-core/src/interfaces/ISablierV2LockupLinear.sol";
import {CouncilMember, IPRBProxy} from "../src/core/CouncilMember.sol";
import {TestTelcoin} from "./mock/TestTelcoin.sol";
import {MockProxyTarget} from "./mock/MockProxyTarget.sol";
import {PRBProxy} from "./mock/MockPRBProxy.sol";
import {PRBProxyRegistry} from "./mock/MockPRBProxyRegistry.sol";
import {UD60x18} from "@prb/math/src/UD60x18.sol";
import {LockupLinear, Broker, IERC20} from "@sablier/v2-core/src/types/DataTypes.sol";
import {IERC20 as IERC20OZ} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
contract PocTest is Test {
    //
    CONSTANTS
    //
    bytes32 public constant GOVERNANCE_COUNCIL_ROLE = keccak256("GOVERNANCE_COUNCIL_ROLE");
    bytes32 public constant SUPPORT_ROLE = keccak256("SUPPORT_ROLE");
    //
    STORAGE
    //
    /// @notice Poc Users
    address public sablierAdmin;
    address public user;
    /// @notice Sablier contracts
    SablierV2Comptroller public comptroller;
    SablierV2NFTDescriptor public nftDescriptor;
    SablierV2LockupLinear public lockupLinear;
    /// @notice Telcoin contracts
    PRBProxyRegistry public proxyRegistry;
    PRBProxy public stream;
    MockProxyTarget public target;
    CouncilMember public councilMember;
    TestTelcoin public telcoin;
    function setUp() public {
        // Setup users
        _setupUsers();
        // Deploy token
        telcoin = new TestTelcoin(address(this));
        // Deploy Sablier
        _deploySablier();
        // Deploy council member
        councilMember = new CouncilMember();
        // Setup stream
        _setupStream();
        // Setup the council member
        _setupCouncilMember();
    }
    function testPoc() public {
        // Step 1: Mint council NFT to user
        councilMember.mint(user);
        assertEq(councilMember.balanceOf(user), 1);
        // Step 2: Forward time 1 days
        vm.warp(block.timestamp + 1 days);
        // Step 3: All functions calling _retrieve() (mint(), burn(), removeFromOffice()) will fail
        vm.expectRevert(abi.encodeWithSignature("PRBProxy_ExecutionReverted()"));
        councilMember.mint(user);
    }
    function _setupUsers() internal {
        sablierAdmin = makeAddr("sablierAdmin");
        user = makeAddr("user");
    }
    function _deploySablier() internal {
        // Deploy protocol
        comptroller = new SablierV2Comptroller(sablierAdmin);
        nftDescriptor = new SablierV2NFTDescriptor();
        lockupLinear = new SablierV2LockupLinear(
            sablierAdmin,
            ISablierV2Comptroller(address(comptroller)),
            ISablierV2NFTDescriptor(address(nftDescriptor))
        );
    }
    function _setupStream() internal {
        // Deploy proxies
        proxyRegistry = new PRBProxyRegistry();
        stream = PRBProxy(payable(address(proxyRegistry.deploy())));
        target = new MockProxyTarget();
        // Setup stream
        LockupLinear.Durations memory durations = LockupLinear.Durations({
            cliff: 0,
            total: 1 weeks
        });
        UD60x18 fee = UD60x18.wrap(0);
        Broker memory broker = Broker({account: address(0), fee: fee});
        LockupLinear.CreateWithDurations memory params = LockupLinear.CreateWithDurations({
            sender: address(this),
            recipient: address(stream),
            totalAmount: 100e18,
            asset: IERC20(address(telcoin)),
            cancelable: false,
            transferable: false,
            durations: durations,
            broker: broker
        });
        bytes memory data = abi.encodeWithSelector(target.createWithDurations.selector, address(lockupLinear), params, "");
        // Create the stream through the PRBProxy
        telcoin.approve(address(stream), type(uint256).max);
        assertEq(lockupLinear.ownerOf(1), address(stream));
    }
    function _setupCouncilMember() internal {
        // Initialize
        councilMember.initialize(
            IERC20OZ(address(telcoin)),
            "Test Council",
            "TC",
            IPRBProxy(address(stream)), // stream_
            address(target), // target_
            1, // id_
            address(lockupLinear)
        );
        // Grant roles
        councilMember.grantRole(GOVERNANCE_COUNCIL_ROLE, address(this));
        councilMember.grantRole(SUPPORT_ROLE, address(this));
    }
}
```

## Recommendation

```solidity
function _retrieve() internal {
...
// Execute the withdrawal from the _target, which might be a Sablier stream or another protocol
_stream.execute(
_target,
abi.encodeWithSelector(
ISablierV2ProxyTarget.withdrawMax.selector,
actualStream,
_id,
address(this)
)
);
...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service caused by an incorrect argument being supplied to the Sablier withdrawMax function inside the CouncilMember contract. The internal _retrieve() routine is supposed to pull unlocked TELCOIN tokens from a Sablier stream by delegating a call through a PRBProxy (_stream) to a ProxyTarget contract (_target). The code builds the calldata with abi.encodeWithSelector(ISablierV2ProxyTarget.withdrawMax.selector, _target, _id, address(this)). The first parameter after the selector should be the address of the Sablier lockup contract that holds the stream, but the implementation mistakenly passes the _target address itself, which is the ProxyTarget contract. When the PRBProxy executes the delegatecall, the ProxyTarget receives a lockup argument that points back to the ProxyTarget rather than the actual Sablier lockup, causing the underlying withdrawMax call to revert because the lockup contract is not a valid stream contract. As a result, every function that invokes _retrieve() – including mint, burn, and removeFromOffice – reverts with PRBProxy_ExecutionReverted, effectively halting all protocol operations that depend on reward retrieval. The impact is that council members cannot receive streamed rewards, user‑facing transactions fail, and the protocol appears dead even though the underlying Sablier stream still holds the tokens. The condition occurs whenever time has elapsed enough for the stream to have unlocked tokens and any external call triggers _retrieve. The affected parties are token holders, council members, and any role that expects to claim or distribute rewards. The issue was uncovered during a manual audit and reproduced with a proof‑of‑concept that used the real Sablier contracts; it was not visible in tests that employed a mock stream because the mock did not enforce the same delegatecall validation. The bug belongs to the class of incorrect argument ordering or misuse of delegatecall targets, which can silently break contract logic and lead to denial‑of‑service. From a user perspective, transactions that should mint a council NFT or claim rewards simply revert, balances remain unchanged, and no tokens are transferred despite the stream having unlocked funds. The root cause is the wrong parameter passed to withdrawMax; the fix is to replace the _target argument with the actual Sablier lockup contract address (the stream contract) when encoding the calldata, ensuring the delegatecall reaches a valid lockup and the withdrawal succeeds.
