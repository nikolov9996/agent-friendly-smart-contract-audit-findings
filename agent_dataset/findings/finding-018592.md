---
id: 18592
severity: "High"
---

# Incorrect flow of adding liquidity in `UlyssesRouter.sol`

## Description

Usually the router in `AMM` is stateless, i.e. it isn’t supposed to contain any tokens, it is just a wrapper of low-level pool functions to perform user-friendly interactions. The current implementation of `addLiquidity()` assumes that a user firstly transfers tokens to the router and then the router performs the deposit to the pool. However, it is not atomic and requires two transactions. Another user can break in after the first transaction and deposit someone else’s tokens.

## Proof of Concept

The router calls the deposit with `msg.sender` as a receiver of shares:
```solidity
        function addLiquidity(uint256 amount, uint256 minOutput, uint256 poolId) external returns (uint256) {
            UlyssesPool ulysses = getUlyssesLP(poolId);

            amount = ulysses.deposit(amount, msg.sender);

            if (amount < minOutput) revert OutputTooLow();
            return amount;
        }
```
And in deposit pool transfer tokens from `msg.sender`, which is the router:
```solidity
        function deposit(uint256 assets, address receiver) public virtual nonReentrant returns (uint256 shares) {
            // Need to transfer before minting or ERC777s could reenter.
            asset.safeTransferFrom(msg.sender, address(this), assets);

            shares = beforeDeposit(assets);

            require(shares != 0, "ZERO_SHARES");

            _mint(receiver, shares);

            emit Deposit(msg.sender, receiver, assets, shares);
        }
```
First, a user will lose tokens sent to the router, if a malicious user calls `addLiquidity()` after it.

## Recommendation

Transfer tokens to the router via `safeTransferFrom()`:
```solidity
        function addLiquidity(uint256 amount, uint256 minOutput, uint256 poolId) external returns (uint256) {
            UlyssesPool ulysses = getUlyssesLP(poolId);
            address(ulysses.asset()).safeTransferFrom(msg.sender, address(this), amount);

            amount = ulysses.deposit(amount, msg.sender);

            if (amount < minOutput) revert OutputTooLow();
            return amount;
        }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the liquidity‑addition flow of the UlyssesRouter contract. The router’s addLiquidity function is written under the assumption that a user will first transfer the desired amount of the underlying asset to the router in a separate transaction and then invoke addLiquidity, which subsequently calls the pool’s deposit function. This design breaks the atomicity that is expected from a typical AMM router, which should pull the tokens from the user and deposit them in a single, indivisible operation. Because the router does not itself perform the token transfer inside addLiquidity, the pool’s deposit routine uses msg.sender – the router – as the source of the assets. Consequently, any tokens that have already been sent to the router sit idle in its balance awaiting a deposit call. An attacker can monitor the mempool, detect that a user has transferred tokens to the router, and front‑run the user’s subsequent addLiquidity call by invoking addLiquidity first. The attacker’s transaction will cause the router to deposit the victim’s tokens into the pool while crediting the attacker’s address with the newly minted LP shares. From the victim’s perspective, the expected outcome – a reduction of their token balance and receipt of a proportional amount of LP tokens – is replaced by a loss of tokens with no corresponding shares, effectively disappearing funds. The impact is a direct theft of user assets and an incorrect accounting of pool liquidity, which can undermine confidence in the protocol. The issue occurs whenever the router is used to add liquidity without an internal safeTransferFrom, i.e., under any condition where a user follows the two‑step pattern of first sending tokens and then calling addLiquidity. It affects all participants who rely on the router for liquidity provision, not just a single address. The flaw was discovered during a formal audit by Code4rena, where the auditors identified that the router’s logic does not enforce atomic token movement and therefore is vulnerable to front‑running. The problem is subtle because the router appears to be a simple wrapper and the missing transfer is not obvious from the function signature; developers may assume that the router already holds the tokens after the first transaction. To remediate the issue, the addLiquidity implementation should be changed to pull the assets directly from the caller using a safeTransferFrom call before invoking the pool’s deposit function. This makes the operation atomic, eliminates the window for an attacker to intervene, and aligns the router with the standard stateless design of AMM routers. In summary, the bug is a classic case of non‑atomic token handling leading to a front‑runable liquidity addition, resulting in loss of user funds and incorrect LP share allocation.
