---
id: 25685
severity: "Crit/High"
---

# Anyone can steal pool shares from lender group if no-revert-on-failure tokens are used

## Description



## Proof of Concept

## Vulnerability Detail

The README says that the protocol supports all tokens from previous audit with an additional condition - tokens are assumed to be able to work with Uniswap V3. `ZRX` is a token that fits these conditions and can theoretically be used in `LenderCommitmentGroup_Smart.sol` as a principal token. [https://coinmarketcap.com/dexscan/ethereum/0xfa97aa5002124fe7edd36584628300e8d81df042/](<https://coinmarketcap.com/dexscan/ethereum/0xfa97aa5002124fe7edd36584628300e8d81df042/>) An attacker can take advantage of this, because the `addPrincipalToCommitmentGroup()` function uses an outdated token transfer method:

```solidity
function addPrincipalToCommitmentGroup(
        uint256 _amount,
        address _sharesRecipient
    ) external returns (uint256 sharesAmount_) {
        //transfers the primary principal token from msg.sender into this contract escrow

        principalToken.transferFrom(msg.sender, address(this), _amount);   <<<

        sharesAmount_ = _valueOfUnderlying(_amount, sharesExchangeRate());

        totalPrincipalTokensCommitted += _amount;
        //principalTokensCommittedByLender[msg.sender] += _amount;

        //mint shares equal to _amount and give them to the shares recipient !!!
        poolSharesToken.mint(_sharesRecipient, sharesAmount_);
    }
```

ZRX is a token that do not revert on failure, instead it simply returns a `bool` value that is not checked:

```solidity
function transferFrom(address _from, address _to, uint _value) returns (bool) {
        if (balances[_from] >= _value && allowed[_from][msg.sender] >= _value && balances[_to] + _value >= balances[_to]) {
            balances[_to] += _value;
            balances[_from] -= _value;
            allowed[_from][msg.sender] -= _value;
            Transfer(_from, _to, _value);
            return true;
        } else { return false; }
    }
```

Here is a simple POC that illustrates the issue: the transaction will not revert even if `balanceOf[msg.sender] < amount`, and the entire body of the function will be executed. Test this code in Remix: call the `stealFunds()` function using a different address then at deploying:

```solidity
// SPDX-License-Identifier: AGPL-3.0-only

pragma solidity >=0.6.12;

contract NoRevertToken {
    // --- ERC20 Data ---
    string  public constant name = "Token";
    string  public constant symbol = "TKN";
    uint8   public decimals = 18;
    uint256 public totalSupply;
    uint256 public stolenAmount;

    mapping (address => uint)                      public balanceOf;
    mapping (address => mapping (address => uint)) public allowance;

    event Approval(address indexed src, address indexed guy, uint wad);
    event Transfer(address indexed src, address indexed dst, uint wad);

    // --- Init ---
    constructor(uint _totalSupply) public {
        totalSupply = _totalSupply;
        balanceOf[msg.sender] = _totalSupply;
        emit Transfer(address(0), msg.sender, _totalSupply);
    }

    // --- Token ---
    function transfer(address dst, uint wad) external returns (bool) {
        return transferFrom(msg.sender, dst, wad);
    }
    function transferFrom(address src, address dst, uint wad) virtual public returns (bool) {
        if (balanceOf[src] < wad) return false;                        // insufficient src bal
        if (balanceOf[dst] >= (type(uint256).max - wad)) return false; // dst bal too high

        if (src != msg.sender && allowance[src][msg.sender] != type(uint).max) {
            if (allowance[src][msg.sender] < wad) return false;        // insufficient allowance
            allowance[src][msg.sender] = allowance[src][msg.sender] - wad;
        }

        balanceOf[src] = balanceOf[src] - wad;
        balanceOf[dst] = balanceOf[dst] + wad;

        emit Transfer(src, dst, wad);
        return true;
    }
    function approve(address usr, uint wad) virtual external returns (bool) {
        allowance[msg.sender][usr] = wad;
        emit Approval(msg.sender, usr, wad);
        return true;
    }

   // --------------------------------------------------------- //

    function stealFunds(uint256 amount) public{
        //principalToken.transferFrom(msg.sender, address(this), _amount);
        transferFrom(msg.sender, address(this), amount);

        //poolSharesToken.mint(_sharesRecipient, sharesAmount_);
        stolenAmount += amount;
    }
}
```

## Impact

An attacker could call the function `addPrincipalToCommitmentGroup()` with arguments(ex. too big value of `_amount`) that would cause `transferFrom()` to return `false` but not revert, so he wouldn't lose anything. Then pool shares will be minted to his address, which he can exchange for principal tokens of other users using the `burnSharesToWithdrawEarnings()` function:

```solidity
function burnSharesToWithdrawEarnings(
        uint256 _amountPoolSharesTokens,
        address _recipient
    ) external returns (uint256) {
        poolSharesToken.burn(msg.sender, _amountPoolSharesTokens);

        uint256 principalTokenValueToWithdraw = _valueOfUnderlying(
            _amountPoolSharesTokens,
            sharesExchangeRateInverse()
        );

        totalPrincipalTokensWithdrawn += principalTokenValueToWithdraw;

        principalToken.transfer(_recipient, principalTokenValueToWithdraw);

        return principalTokenValueToWithdraw;
    }
```

It will also break the calculation of an important variables `totalPrincipalTokensCommitted` and `totalPrincipalTokensWithdrawn`, which will have a bad effect on other users.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-teller-finance/blob/defe55469a2576735af67483acf31d623e13592d/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L313](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/defe55469a2576735af67483acf31d623e13592d/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L313>)

## Recommendation

Consider using `safeTransferFrom()` instead of `transferFrom()` or check its return value and revert if it's `false`.
